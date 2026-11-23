// SPDX-License-Identifier: GPL-3.0-or-later
// Browser test of WebP, GIF and HEIC pictures (TO-DO 8.19, a0.6.3), against
// the REAL routes on Parseh's handler (tests/studio_harness.py parseh: a
// temporary library, exercises/ and clip tray):
//   a) the studio editor's Image button takes a WebP, a GIF and a HEIC; the
//      WebP and the GIF are stored byte for byte, the HEIC as an upright JPEG
//      (img_0042.jpg), each put in on a line of its own and shown by the
//      preview; a BMP is refused in words that name the formats
//   b) a deck's exercise form: Upload… beside "Front image path" takes a WebP
//      and a HEIC, the field names the deck's copy, the card is saved, and the
//      deck serves the picture as image/webp and image/jpeg
// The pictures are made for this run by $PARSEH_PYTHON with Pillow and
// pillow-heif; without pillow-heif the HEIC parts are skipped, saying so.
//   CHROME_BIN=... PARSEH_PYTHON=<a Python with Pillow> deno run --allow-all tests/picture_formats.mjs
import {chromium} from 'npm:playwright-core@1.52.0';
import {Buffer} from 'node:buffer';

const root = await Deno.realPath(new URL('..', import.meta.url));
const python = Deno.env.get('PARSEH_PYTHON') || 'python3';
let passed = 0, skipped = [];
const assert = (v, m) => { if (!v) throw Error('FAIL: ' + m); passed++; console.log('  ok', m); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, what, ms = 20000) {
  const end = Date.now() + ms;
  for (;;) {
    let v;
    try { v = await fn(); } catch (_) { v = false; }
    if (v) return v;
    if (Date.now() > end) throw Error('FAIL: timed out: ' + what);
    await sleep(60);
  }
}

/* The pictures, made by Python: a WebP 40 x 20, a GIF of two frames, a HEIC
   40 x 20 whose EXIF says to turn it (shown 20 x 40), and a BMP. */
const MADE = await (async () => {
  const code = `
import base64, io, json
out = {}
try:
    from PIL import Image
except ImportError:
    print(json.dumps({"pillow": False})); raise SystemExit
im = Image.new("RGB", (40, 20), (30, 120, 220)); b = io.BytesIO(); im.save(b, "WEBP"); out["webp"] = b.getvalue()
f1 = Image.new("RGB", (30, 30), (230, 40, 40)); f2 = Image.new("RGB", (30, 30), (40, 200, 40))
b = io.BytesIO(); f1.save(b, "GIF", save_all=True, append_images=[f2], duration=200, loop=0); out["gif"] = b.getvalue()
b = io.BytesIO(); im.save(b, "BMP"); out["bmp"] = b.getvalue()
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    h = Image.new("RGB", (40, 20), (255, 0, 0)); h.paste((0, 0, 255), (20, 0, 40, 20))
    exif = Image.Exif(); exif[0x0112] = 6
    b = io.BytesIO(); h.save(b, "HEIF", exif=exif.tobytes(), quality=95); out["heic"] = b.getvalue()
except ImportError:
    pass
print(json.dumps(dict({k: base64.b64encode(v).decode() for k, v in out.items()}, pillow=True)))
`;
  const r = await new Deno.Command(python, {args: ['-c', code], stdout: 'piped', stderr: 'piped'}).output();
  if (!r.success) throw Error('making the pictures: ' + new TextDecoder().decode(r.stderr));
  const j = JSON.parse(new TextDecoder().decode(r.stdout).trim().split('\n').pop());
  if (!j.pillow) throw Error(`${python} has no Pillow: set PARSEH_PYTHON to a Python with Pillow (environment.yml lists it)`);
  const out = {};
  for (const k of ['webp', 'gif', 'bmp', 'heic']) if (j[k]) out[k] = Buffer.from(j[k], 'base64');
  return out;
})();
const HEIC = !!MADE.heic;
if (!HEIC) skipped.push(`the HEIC parts: ${python} has no pillow-heif to make one with`);

async function startHarness() {
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
  return {proc, info, log};
}

const {proc, info, log} = await startHarness();
const origin = `http://127.0.0.1:${info.port}`, base = info.studio;
const url = p => origin + base + p;
const browser = await chromium.launch({executablePath: Deno.env.get('CHROME_BIN'), headless: true});
let failed = null;
try {
  const page = await (await browser.newContext({viewport: {width: 1400, height: 900}})).newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const api = async (method, path, body) => {
    const r = await fetch(url(path), {method, headers: body ? {'Content-Type': 'application/json'} : {},
                                      body: body ? JSON.stringify(body) : undefined});
    const data = await r.json();
    if (!r.ok) throw Error(`${method} ${path}: ${r.status} ${JSON.stringify(data)}`);
    return data;
  };
  const source = () => page.locator('#src').inputValue();
  const toastSays = (re, what) => until(async () => re.test(await page.locator('#toast').textContent()), what);
  const same = (a, b) => Buffer.from(a).equals(Buffer.from(b));
  // the preview's picture of that name, loaded: its natural size
  const shown = name => until(async () => page.evaluate(n => {
    const i = [...document.querySelectorAll('#sheet img')].find(i => (i.getAttribute('src') || '').includes('/images/' + n));
    return i && i.complete && i.naturalWidth > 0 && {w: i.naturalWidth, h: i.naturalHeight};
  }, name), `the preview shows ${name}`);

  /* ---------------- a) the studio editor ---------------- */
  console.log('a) the studio editor');
  const id = (await api('POST', '/api/docs', {markdown: '---\ntitle: Pictures\ntarget: fa\n---\n\nPictures of every kind.\n'})).meta.id;
  let docDir = null;
  for await (const d of Deno.readDir(info.library))
    try { await Deno.stat(`${info.library}/${d.name}/${id}`); docDir = `${info.library}/${d.name}/${id}`; } catch (_) { /* not here */ }
  await page.goto(url(`/doc/${id}/edit`));
  await until(async () => /rendered/.test(await page.locator('#pv-status').textContent()), 'the preview renders');
  const accept = await page.locator('#img-upload').getAttribute('accept');
  assert(/image\/webp/.test(accept) && /image\/gif/.test(accept) && /\.heic/.test(accept), `the Image picker offers WebP, GIF and HEIC (${accept})`);
  const pick = async (name, mimeType, buffer) => {
    await page.locator('#src').evaluate(t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
    const chooser = page.waitForEvent('filechooser');
    await page.locator('label[for="img-upload"]').click();
    await (await chooser).setFiles({name, mimeType, buffer});
  };
  await pick('Band.webp', 'image/webp', MADE.webp);
  await until(async () => (await source()).includes('](images/band.webp)'), 'the WebP\'s line goes in');
  assert(same(await Deno.readFile(docDir + '/images/band.webp'), MADE.webp), 'the WebP is stored as it came, byte for byte');
  const w = await shown('band.webp');
  assert(w.w === 40 && w.h === 20, `the preview shows the WebP (${w.w} x ${w.h})`);
  await pick('Moving.gif', 'image/gif', MADE.gif);
  await until(async () => (await source()).includes('](images/moving.gif)'), 'the GIF\'s line goes in');
  assert(same(await Deno.readFile(docDir + '/images/moving.gif'), MADE.gif), 'the GIF is stored as it came, both frames');
  await shown('moving.gif');
  assert(true, 'the preview shows the GIF');
  if (HEIC) {
    // a browser often gives a HEIC no type at all: the name is enough
    await pick('IMG_0042.HEIC', '', MADE.heic);
    await until(async () => (await source()).includes('](images/img_0042.jpg)'), 'the HEIC goes in as a JPEG');
    await toastSays(/Uploaded img_0042\.jpg/, 'the upload is told, by the JPEG\'s name');
    assert(true, 'the upload is told by the JPEG\'s name');
    const jpeg = await Deno.readFile(docDir + '/images/img_0042.jpg');
    assert(jpeg[0] === 0xff && jpeg[1] === 0xd8, 'what is stored is a JPEG');
    let heicLeft = false;
    for await (const f of Deno.readDir(docDir + '/images')) if (/\.hei[cf]$/i.test(f.name)) heicLeft = true;
    assert(!heicLeft, 'and no HEIC is kept beside it');
    const h = await shown('img_0042.jpg');
    assert(h.w === 20 && h.h === 40, `the preview shows it upright, as the phone held it (${h.w} x ${h.h})`);
    // dropped on the editor, the same way
    await page.locator('#src').evaluate(t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); });
    const dt = await page.evaluateHandle(b64 => {
      const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
      const d = new DataTransfer(); d.items.add(new File([bytes], 'Dropped.heic', {type: ''})); return d;
    }, MADE.heic.toString('base64'));
    await page.locator('.editor-pane').dispatchEvent('drop', {dataTransfer: dt});
    await until(async () => (await source()).includes('](images/dropped.jpg)'), 'a HEIC dropped on the editor goes in as a JPEG');
    assert(true, 'a HEIC dropped on the editor, with no type, goes in as a JPEG');
  }
  await pick('old.bmp', 'image/bmp', MADE.bmp);
  await toastSays(/only PNG, JPEG, WebP, GIF, HEIC, SVG and PDF pictures can be added/, 'a BMP is refused, in words that name the formats');
  assert(true, 'a BMP is refused, in words that name the formats');

  /* ---------------- b) a deck's exercise form ---------------- */
  console.log('b) a deck');
  const made = await (await fetch(origin + '/exercises/api/decks', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                                                     body: JSON.stringify({name: 'Pictures', lang: 'fa'})})).json();
  const deck = made.deck;
  await page.goto(`${origin}/exercises/deck/${deck.folder}/${deck.slug}/`);
  const form = page.locator('.ex-form-modal');
  const fieldOf = label => form.locator('label.ex-author-field').filter({has: page.locator(`span:text-is("${label}")`)});
  const boxOf = label => fieldOf(label).locator('input:not([type=file]), textarea').first();
  const card = async (word, file, name, mimeType, path, type) => {
    await page.locator('#btn-add-exercise').click();
    await page.locator('.ex-type', {hasText: 'Embedded vocabulary flashcard'}).click();
    await form.waitFor();
    await boxOf('Word or expression').fill(word);
    await boxOf('Meaning').fill('a picture');
    const chooser = page.waitForEvent('filechooser');
    await fieldOf('Front image path').locator('.ex-upload-row button', {hasText: 'Upload…'}).click();
    await (await chooser).setFiles({name, mimeType, buffer: file});
    await until(async () => (await boxOf('Front image path').inputValue()) === path, `the field names the deck's ${path}`);
    assert(true, `${name}: the field names the deck's copy, ${path}`);
    await form.locator('[data-x="save"]').click();
    await form.waitFor({state: 'detached'});
    const r = await fetch(`${origin}/exercises/media/${deck.folder}/${deck.slug}/${path}`);
    const bytes = new Uint8Array(await r.arrayBuffer());
    assert(r.status === 200 && r.headers.get('content-type') === type, `the deck serves it as ${type}`);
    return bytes;
  };
  const webp = await card('آبی', MADE.webp, 'Sky.webp', 'image/webp', 'images/sky.webp', 'image/webp');
  assert(same(webp, MADE.webp), 'the deck\'s WebP is the one uploaded, byte for byte');
  if (HEIC) {
    const jpeg = await card('سرخ', MADE.heic, 'IMG_9.HEIC', '', 'images/img_9.jpg', 'image/jpeg');
    assert(jpeg[0] === 0xff && jpeg[1] === 0xd8, 'the deck\'s HEIC is a JPEG');
  }
  const items = (await (await fetch(`${origin}/exercises/api/decks/${deck.folder}/${deck.slug}`)).json()).items;
  assert(items.length === (HEIC ? 2 : 1) && items.every(i => !(i.warnings || []).length), 'the cards are in the deck, with nothing to warn of');
  // the deck's page draws the card with its picture
  await page.goto(`${origin}/exercises/deck/${deck.folder}/${deck.slug}/`);
  assert(errors.length === 0, 'no page error: ' + errors.join(' | '));
} catch (e) {
  failed = e;
} finally {
  await browser.close();
  proc.kill('SIGTERM');
  await proc.status;
}
if (failed) { console.error(failed.message || failed); console.error(log.join('').slice(-3000)); Deno.exit(1); }
for (const s of skipped) console.log('  SKIPPED', s);
console.log(`\npicture_formats: ${passed} checks passed${skipped.length ? ', ' + skipped.length + ' part(s) skipped' : ''}`);
